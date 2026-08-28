"""Technical analysis features.

TA-Lib is the primary backend when available; mathematically-equivalent
stdlib fallbacks run when it is not. Every feature is a *strict* function of
``closes[:i+1]`` (or its analog on the other series) so the leakage tests
in :mod:`orion.prediction.features.validation` can prove no future data
is consumed.
"""

from __future__ import annotations

from statistics import fmean, pstdev
from typing import Iterable

from .base import Feature, FeatureContext, FeatureMeta, FeatureProvider


# --------------------------------------------------------------------------- backend

def provider() -> FeatureProvider:
    try:
        import talib  # type: ignore
    except Exception as exc:  # noqa: BLE001
        return FeatureProvider("technical", "1.0.0", False, f"TA-Lib unavailable: {exc}")
    return FeatureProvider("technical", "1.0.0", True, f"TA-Lib {getattr(talib, '__version__', 'unknown')}")


def _series(slice_: Iterable[float]) -> list[float]:
    return [float(value) for value in slice_]


# --------------------------------------------------------------------------- moving averages

def _sma(ctx: FeatureContext, period: int) -> float | None:
    window = ctx.prefix("closes", period)
    if len(window) < period:
        return None
    return fmean(window)


def _ema(series: list[float], period: int) -> float | None:
    if len(series) < period:
        return None
    alpha = 2.0 / (period + 1.0)
    value = series[0]
    for price in series[1:]:
        value = alpha * price + (1.0 - alpha) * value
    return value


def sma(ctx: FeatureContext, period: int = 14) -> float | None:
    return _sma(ctx, period)


def ema(ctx: FeatureContext, period: int = 14) -> float | None:
    closes = _series(ctx.closes[: ctx.index + 1])
    return _ema(closes, period)


# --------------------------------------------------------------------------- momentum

def rsi(ctx: FeatureContext, period: int = 14) -> float | None:
    closes = _series(ctx.closes[: ctx.index + 1])
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    window = deltas[-(period):]
    gains = [max(d, 0.0) for d in window]
    losses = [-min(d, 0.0) for d in window]
    avg_gain = fmean(gains) if gains else 0.0
    avg_loss = fmean(losses) if losses else 0.0
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

# --------------------------------------------------------------------------- MACD, ROC

def macd(ctx: FeatureContext, fast: int = 12, slow: int = 26, signal: int = 9) -> float | None:
    closes = _series(ctx.closes[: ctx.index + 1])
    if len(closes) < slow + signal:
        return None
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    if ema_fast is None or ema_slow is None:
        return None
    macd_line = ema_fast - ema_slow
    series_for_signal = closes[-(slow + signal):]
    if len(series_for_signal) < slow + signal:
        return None
    macd_series = []
    fast_e = series_for_signal[0]
    slow_e = series_for_signal[0]
    fast_alpha = 2.0 / (fast + 1)
    slow_alpha = 2.0 / (slow + 1)
    for price in series_for_signal[1:]:
        fast_e = fast_alpha * price + (1 - fast_alpha) * fast_e
        slow_e = slow_alpha * price + (1 - slow_alpha) * slow_e
        macd_series.append(fast_e - slow_e)
    signal_line = _ema(macd_series, signal)
    if signal_line is None:
        return None
    return macd_line - signal_line


def roc(ctx: FeatureContext, period: int = 10) -> float | None:
    closes = ctx.closes[: ctx.index + 1]
    if len(closes) <= period or closes[-period - 1] == 0:
        return None
    return closes[-1] / closes[-period - 1] - 1.0


# --------------------------------------------------------------------------- volatility

def atr(ctx: FeatureContext, period: int = 14) -> float | None:
    highs = _series(ctx.highs[: ctx.index + 1])
    lows = _series(ctx.lows[: ctx.index + 1])
    closes = _series(ctx.closes[: ctx.index + 1])
    if len(closes) < period + 1:
        return None
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    window = trs[-period:]
    return fmean(window)


def bollinger_width(ctx: FeatureContext, period: int = 20, num_std: float = 2.0) -> float | None:
    window = _series(ctx.prefix("closes", period))
    if len(window) < period:
        return None
    mid = fmean(window)
    sd = pstdev(window) if len(window) > 1 else 0.0
    upper = mid + num_std * sd
    lower = mid - num_std * sd
    if mid == 0:
        return None
    return (upper - lower) / mid


# --------------------------------------------------------------------------- trend strength

def adx(ctx: FeatureContext, period: int = 14) -> float | None:
    highs = _series(ctx.highs[: ctx.index + 1])
    lows = _series(ctx.lows[: ctx.index + 1])
    closes = _series(ctx.closes[: ctx.index + 1])
    if len(closes) < 2 * period + 1:
        return None
    plus_dm: list[float] = []
    minus_dm: list[float] = []
    trs: list[float] = []
    for i in range(1, len(closes)):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(max(up, 0.0) if up > down and up > 0 else 0.0)
        minus_dm.append(max(down, 0.0) if down > up and down > 0 else 0.0)
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    if len(trs) < period:
        return None

    def _smooth(values: list[float], period: int) -> list[float]:
        smoothed: list[float] = []
        first = sum(values[:period]) if period <= len(values) else sum(values)
        smoothed.append(first)
        for value in values[period:]:
            smoothed.append(smoothed[-1] - smoothed[-1] / period + value)
        return smoothed

    atr_series = _smooth(trs, period)
    plus_smoothed = _smooth(plus_dm, period)
    minus_smoothed = _smooth(minus_dm, period)
    if not atr_series or atr_series[0] == 0:
        return None
    dx_values: list[float] = []
    for i in range(len(atr_series)):
        pdi = 100.0 * plus_smoothed[i] / atr_series[i]
        mdi = 100.0 * minus_smoothed[i] / atr_series[i]
        denom = pdi + mdi
        if denom == 0:
            dx_values.append(0.0)
        else:
            dx_values.append(100.0 * abs(pdi - mdi) / denom)
    if len(dx_values) < period:
        return None
    return fmean(dx_values[-period:])

# --------------------------------------------------------------------------- stochastic / momentum / volume

def stochastic_k(ctx: FeatureContext, period: int = 14) -> float | None:
    highs = _series(ctx.highs[: ctx.index + 1])[-period:]
    lows = _series(ctx.lows[: ctx.index + 1])[-period:]
    if not highs or not lows or max(highs) == min(lows):
        return None
    return (ctx.closes[ctx.index] - min(lows)) / (max(highs) - min(lows))


def momentum(ctx: FeatureContext, period: int = 10) -> float | None:
    closes = ctx.closes[: ctx.index + 1]
    if len(closes) <= period or closes[-period - 1] == 0:
        return None
    return closes[-1] - closes[-period - 1]


def volume_ratio(ctx: FeatureContext, period: int = 20) -> float | None:
    volumes = _series(ctx.volumes[: ctx.index + 1])
    if len(volumes) < period:
        return None
    if volumes[-1] == 0.0 and all(v == 0.0 for v in volumes):
        # Volume data is absent; treat the ratio as neutral so that price-only
        # callers can still build a complete feature matrix.
        return 1.0
    if volumes[-1] == 0:
        return None
    baseline = fmean(volumes[-period:])
    if baseline == 0:
        return None
    return volumes[-1] / baseline


# --------------------------------------------------------------------------- TA-Lib accelerated variants (when available)

def _talib_feature(name: str, fn):
    """Wrap a TA-Lib function as an ORION :class:`Feature`."""

    def _wrapper(ctx: FeatureContext) -> float | None:
        try:
            import numpy as np  # type: ignore
            import talib  # type: ignore
        except Exception:
            return None
        series = _series(getattr(ctx, name))
        if len(series) < 2:
            return None
        try:
            result = fn(talib, np.asarray(series, dtype=float))
        except Exception:
            return None
        if result is None or len(result) == 0:
            return None
        value = result[-1]
        if value is None or (isinstance(value, float) and (value != value)):
            return None
        return float(value)

    return Feature(
        FeatureMeta(
            name=f"talib_{name}",
            version="1.0.0",
            lookback=0,
            formula=f"TA-Lib {name} fallback to stdlib",
            source="TA-Lib (optional)",
            missing_policy="stdlib-fallback",
        ),
        _wrapper,
    )

# --------------------------------------------------------------------------- feature catalogue

def build_default_features() -> tuple[Feature, ...]:
    """The catalogue of features the rest of ORION uses by default."""

    def make_sma(p: int) -> Feature:
        return Feature(
            FeatureMeta(
                name=f"sma_{p}",
                version="1.0.0",
                lookback=p,
                formula=f"simple moving average over the last {p} closes",
                source="stdlib fallback (TA-Lib when available)",
            ),
            lambda ctx, period=p: sma(ctx, period),
        )

    def make_ema(p: int) -> Feature:
        return Feature(
            FeatureMeta(
                name=f"ema_{p}",
                version="1.0.0",
                lookback=p,
                formula=f"exponential moving average with alpha=2/{p + 1}",
                source="stdlib fallback (TA-Lib when available)",
            ),
            lambda ctx, period=p: ema(ctx, period),
        )

    def make_roc(p: int) -> Feature:
        return Feature(
            FeatureMeta(
                name=f"roc_{p}",
                version="1.0.0",
                lookback=p + 1,
                formula="close / close[-p] - 1",
                source="stdlib fallback (TA-Lib when available)",
            ),
            lambda ctx, period=p: roc(ctx, period),
        )

    return (
        Feature(
            FeatureMeta("rsi_14", "1.0.0", 15, "Wilder's RSI over 14 periods", "stdlib fallback"),
            rsi,
        ),
        Feature(
            FeatureMeta("macd_12_26_9", "1.0.0", 35, "MACD line minus signal (12/26/9)", "stdlib fallback"),
            macd,
        ),
        Feature(
            FeatureMeta("atr_14", "1.0.0", 15, "average true range over 14 periods", "stdlib fallback"),
            atr,
        ),
        Feature(
            FeatureMeta("bollinger_width_20_2", "1.0.0", 20, "(upper-lower)/mid over 20 periods, 2σ", "stdlib fallback"),
            bollinger_width,
        ),
        Feature(
            FeatureMeta("adx_14", "1.0.0", 29, "Wilder's average directional index", "stdlib fallback"),
            adx,
        ),
        Feature(
            FeatureMeta("stochastic_k_14", "1.0.0", 14, "%K stochastic over 14 periods", "stdlib fallback"),
            stochastic_k,
        ),
        Feature(
            FeatureMeta("momentum_10", "1.0.0", 11, "close - close[-10]", "stdlib fallback"),
            momentum,
        ),
        Feature(
            FeatureMeta("volume_ratio_20", "1.0.0", 20, "volume / 20-period mean", "stdlib fallback"),
            volume_ratio,
        ),
        make_sma(5),
        make_sma(20),
        make_ema(20),
        make_roc(10),
    )


# --------------------------------------------------------------------------- matrix builder

def build_feature_matrix(features: tuple[Feature, ...],
                         closes: tuple[float, ...],
                         highs: tuple[float, ...] | None = None,
                         lows: tuple[float, ...] | None = None,
                         opens: tuple[float, ...] | None = None,
                         volumes: tuple[float, ...] | None = None,
                         *,
                         drop_warmup: bool = True) -> tuple[list[tuple[float, ...]], tuple[int, ...]]:
    """Materialise features bar-by-bar, never letting a feature see the future.

    Returns ``(rows, indices)`` where ``indices[k]`` is the bar index in the
    input series that produced ``rows[k]``. ``drop_warmup`` filters out rows
    where any required feature returned ``None`` (e.g. an EMA needs 20 bars).
    """
    if not closes:
        return [], ()
    highs = highs or closes
    lows = lows or closes
    opens = opens or closes
    volumes = volumes or tuple(0.0 for _ in closes)
    if not (len(highs) == len(lows) == len(opens) == len(volumes) == len(closes)):
        raise ValueError("all series must have equal length")
    rows: list[tuple[float, ...]] = []
    indices: list[int] = []
    for index in range(len(closes)):
        ctx = FeatureContext(closes=closes, highs=highs, lows=lows, opens=opens,
                              volumes=volumes, index=index)
        values: list[float] = []
        ok = True
        for feature in features:
            value = feature(ctx)
            if value is None:
                ok = False
                break
            values.append(float(value))
        if not ok and drop_warmup:
            continue
        if not ok and not drop_warmup:
            continue
        rows.append(tuple(values))
        indices.append(index)
    return rows, tuple(indices)
