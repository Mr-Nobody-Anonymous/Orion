"""Drift monitoring.

Implements the Population Stability Index (PSI) on the prediction
distribution.  PSI is the standard, vendor-neutral drift metric used in
credit risk and fraud.  Two distributions are compared by binning both
and computing ``sum((actual - expected) * ln(actual / expected))``.

  * PSI < 0.1: no drift
  * 0.1 <= PSI < 0.2: small drift
  * PSI >= 0.2: significant drift
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


def _safe_proportion(p: float) -> float:
    return max(p, 1e-6)


def _psi_one_bin(expected_p: float, actual_p: float) -> float:
    return (actual_p - expected_p) * math.log(
        _safe_proportion(actual_p) / _safe_proportion(expected_p)
    )


def population_stability_index(
    reference: Sequence[float],
    actual: Sequence[float],
    *,
    n_bins: int = 10,
) -> float:
    """Population Stability Index between two score samples."""
    if not reference or not actual:
        return 0.0
    if min(reference) == max(reference) and min(actual) == max(actual):
        return 0.0
    lo = min(min(reference), min(actual))
    hi = max(max(reference), max(actual))
    if hi == lo:
        return 0.0
    step = (hi - lo) / n_bins

    def bucketise(s: Sequence[float]) -> list[int]:
        out = [0] * n_bins
        for x in s:
            idx = int((x - lo) / step)
            if idx >= n_bins:
                idx = n_bins - 1
            if idx < 0:
                idx = 0
            out[idx] += 1
        return out

    expected = bucketise(reference)
    actual_b = bucketise(actual)
    psi = 0.0
    for i in range(n_bins):
        e = expected[i] / len(reference)
        a = actual_b[i] / len(actual)
        psi += _psi_one_bin(e, a)
    return psi


@dataclass(frozen=True, slots=True)
class DriftAssessment:
    psi: float
    n_reference: int
    n_actual: int
    alert: bool
    severity: str  # "none" | "small" | "significant"


def assess(reference: Sequence[float], actual: Sequence[float], *, threshold: float = 0.2) -> DriftAssessment:
    psi = population_stability_index(reference, actual)
    if psi < 0.1:
        severity = "none"
        alert = False
    elif psi < threshold:
        severity = "small"
        alert = False
    else:
        severity = "significant"
        alert = True
    return DriftAssessment(
        psi=psi,
        n_reference=len(reference),
        n_actual=len(actual),
        alert=alert,
        severity=severity,
    )
