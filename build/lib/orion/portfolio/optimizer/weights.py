"""Weight container shared by all ORION portfolio optimisers."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

__all__ = ["Weights", "normalise_weights"]


@dataclass(frozen=True, slots=True)
class Weights:
    """Mapping ``symbol -> weight`` plus metadata about how it was built."""

    weights: Mapping[str, float]
    method: str
    notes: tuple[str, ...] = ()
    diagnostics: Mapping[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "weights": dict(self.weights),
            "method": self.method,
        }
        if self.notes:
            out["notes"] = list(self.notes)
        if self.diagnostics:
            out["diagnostics"] = dict(self.diagnostics)
        return out

    def __iter__(self):
        return iter(self.weights)

    def items(self):
        return self.weights.items()

    def symbols(self) -> tuple[str, ...]:
        return tuple(self.weights)


def _to_symbols(symbols: Sequence[str] | None, expected_returns: Mapping[str, float]) -> tuple[str, ...]:
    if symbols is None:
        return tuple(expected_returns)
    return tuple(symbols)


def normalise_weights(
    weights: Mapping[str, float],
    *,
    long_only: bool = True,
    gross_exposure: float = 1.0,
) -> dict[str, float]:
    """Rescale weights to a given gross exposure, optionally making them
    long-only and clipping negatives."""
    if not weights:
        raise ValueError("weights must be non-empty")
    if gross_exposure < 0:
        raise ValueError("gross_exposure must be non-negative")
    items = list(weights.items())
    if long_only:
        items = [(s, max(0.0, w)) for s, w in items]
    total = sum(w for _, w in items)
    if total <= 0:
        # Degenerate: split evenly.
        n = len(items)
        even = gross_exposure / n if n else 0.0
        return {s: even for s, _ in items}
    return {s: w / total * gross_exposure for s, w in items}
