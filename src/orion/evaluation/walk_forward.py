"""Contamination-safe walk-forward harness with embargo and purge.

A walk-forward evaluation slices the price history into a sequence of
(train, test) pairs.  The test window is always *strictly after* the
train window; an ``embargo`` of additional bars is dropped between
train and test to remove any leakage from the most recent training
samples; a ``purge`` of bars is dropped at the start of every test
window to remove any leakage from the most recent test samples.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_id: int
    train_start: int
    train_end: int  # inclusive
    embargo: int
    purge: int
    test_start: int
    test_end: int  # inclusive

    def __post_init__(self) -> None:
        if self.train_start < 0:
            raise ValueError("train_start must be non-negative")
        if self.train_end < self.train_start:
            raise ValueError("train_end must be >= train_start")
        if self.embargo < 0 or self.purge < 0:
            raise ValueError("embargo and purge must be non-negative")
        if self.test_start <= self.train_end + self.embargo:
            raise ValueError(
                f"test_start ({self.test_start}) must be > train_end ({self.train_end}) "
                f"+ embargo ({self.embargo})"
            )
        if self.test_end < self.test_start:
            raise ValueError("test_end must be >= test_start")


def build_folds(
    n: int,
    *,
    train_size: int,
    test_size: int,
    step: int = 1,
    embargo: int = 0,
    purge: int = 0,
) -> list[WalkForwardFold]:
    """Build the list of folds covering the bar range ``[0, n)``."""
    if train_size <= 0 or test_size <= 0 or step <= 0:
        raise ValueError("train_size, test_size and step must be positive")
    if n < train_size + test_size + embargo + purge:
        raise ValueError(
            f"price series of length {n} is too short for train_size={train_size}, "
            f"test_size={test_size}, embargo={embargo}, purge={purge}"
        )
    folds: list[WalkForwardFold] = []
    fold_id = 0
    train_start = 0
    while True:
        train_end = train_start + train_size - 1
        test_start = train_end + 1 + embargo + purge
        test_end = test_start + test_size - 1
        if test_end >= n:
            break
        folds.append(
            WalkForwardFold(
                fold_id=fold_id,
                train_start=train_start,
                train_end=train_end,
                embargo=embargo,
                purge=purge,
                test_start=test_start,
                test_end=test_end,
            )
        )
        fold_id += 1
        train_start += step
    return folds


PredictFn = Callable[[Sequence[float]], float]


def run_fold(
    fold: WalkForwardFold,
    prices: Sequence[float],
    predictor: PredictFn,
) -> float:
    """Run one fold: predict the *average* test return given the train
    history, then return the realised average return over the test
    window.  The realised value is the benchmark against which the
    prediction is scored.
    """
    train_prices = prices[fold.train_start : fold.train_end + 1]
    test_prices = prices[fold.test_start : fold.test_end + 1]
    prediction = predictor(train_prices)
    if len(test_prices) < 2:
        realised = 0.0
    else:
        realised = test_prices[-1] / test_prices[0] - 1.0
    return _scored_error(prediction, realised)


def _scored_error(prediction: float, realised: float) -> float:
    """Signed error: ``prediction - realised``.

    Sign convention: positive = over-prediction, negative = under-prediction.
    A *good* predictor is one whose errors average toward zero and whose
    absolute errors are small.
    """
    return prediction - realised
