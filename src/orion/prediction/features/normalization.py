"""Z-score normalization for feature matrices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import math


@dataclass(frozen=True, slots=True)
class ZScoreNormalizer:
    means: tuple[float, ...]
    stds: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.means) != len(self.stds):
            raise ValueError("means and stds must have equal length")
        for value in self.stds:
            if value < 0.0:
                raise ValueError("stds must be non-negative")

    def apply(self, row: Sequence[float]) -> tuple[float, ...]:
        if len(row) != len(self.means):
            raise ValueError("row length must match normalizer length")
        return tuple(
            0.0 if std == 0.0 else (value - mean) / std
            for value, mean, std in zip(row, self.means, self.stds)
        )


def fit_zscore(matrix: Sequence[Sequence[float]]) -> ZScoreNormalizer:
    if not matrix:
        raise ValueError("matrix is empty")
    width = len(matrix[0])
    if width == 0:
        raise ValueError("matrix has no columns")
    if any(len(row) != width for row in matrix):
        raise ValueError("all rows must have equal width")
    means = [sum(row[i] for row in matrix) / len(matrix) for i in range(width)]
    stds = []
    for i, mean in enumerate(means):
        variance = sum((row[i] - mean) ** 2 for row in matrix) / len(matrix)
        stds.append(math.sqrt(variance))
    return ZScoreNormalizer(tuple(means), tuple(stds))


def apply_zscore(normalizer: ZScoreNormalizer, row: Sequence[float]) -> tuple[float, ...]:
    return normalizer.apply(row)
