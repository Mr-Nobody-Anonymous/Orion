"""Look-ahead leakage detection for features and pipelines.

The :func:`assert_no_lookahead` helper takes a feature function and exercises
it on a synthetic price series with a *trap* value placed after the
evaluation index. If the feature ever returns the trap, it is consuming the
future. The same logic can be applied to any callable that takes a
:class:`FeatureContext` and returns a float-or-None.
"""

from __future__ import annotations

import random
from typing import Callable

from .base import Feature, FeatureContext


class FeatureValidationError(AssertionError):
    """Raised when a feature is observed to consume future data."""


def _build_context(closes: tuple[float, ...], index: int,
                    highs: tuple[float, ...] | None = None,
                    lows: tuple[float, ...] | None = None,
                    opens: tuple[float, ...] | None = None,
                    volumes: tuple[float, ...] | None = None) -> FeatureContext:
    return FeatureContext(
        closes=closes,
        highs=highs if highs is not None else closes,
        lows=lows if lows is not None else closes,
        opens=opens if opens is not None else closes,
        volumes=volumes if volumes is not None else tuple(0.0 for _ in closes),
        index=index,
    )


def _placeholder_closes(length: int, *, seed: int = 0) -> tuple[float, ...]:
    rng = random.Random(seed)
    return tuple(100.0 + rng.random() for _ in range(length))


def _run_with_trap(evaluator: Callable[[FeatureContext], float | None],
                   *, index: int, trap: float, length: int = 60) -> float | None:
    closes = _placeholder_closes(length)
    # Replace the first bar *after* `index` with the trap value; leave the
    # bar at `index` unchanged. A future-conserving feature must not see
    # the trap unless its read range is wrong.
    poisoned = list(closes)
    target = min(index + 1, len(poisoned) - 1)
    poisoned[target] = trap
    ctx = _build_context(tuple(poisoned), index)
    return evaluator(ctx)


def assert_no_lookahead(feature: Feature, *, trials: int = 16, trap: float = 1e9,
                         index: int | None = None) -> None:
    """Run ``feature`` many times; raise if any call returns ``trap``."""

    if index is not None and index < 0:
        raise ValueError("index must be non-negative")
    for seed in range(trials):
        rng_index = (index if index is not None else 20 + seed) + 5
        value = _run_with_trap(feature, index=rng_index, trap=trap, length=rng_index + 5)
        if value is not None and abs(value - trap) < 1e-3:
            raise FeatureValidationError(
                f"feature {feature.meta.name!r} returned a value that matches the "
                "future-only trap — it consumes bars after the evaluation index"
            )


def validate_no_lookahead(features: list[Feature] | tuple[Feature, ...] | Feature,
                          *, trials: int = 16) -> None:
    if isinstance(features, Feature):
        assert_no_lookahead(features, trials=trials)
        return
    for feature in features:
        assert_no_lookahead(feature, trials=trials)
