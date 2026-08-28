"""Feature abstractions and provider status.

Every feature carries a :class:`FeatureMeta` describing its name, version,
lookback, formula/source, missing-value behaviour, and a ``uses_future`` flag
that must always be ``False`` — features that consume future observations
violate the chronological contract enforced by the validation tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

FeatureFn = Callable[["FeatureContext"], float | None]


@dataclass(frozen=True, slots=True)
class FeatureMeta:
    name: str
    version: str
    lookback: int
    formula: str
    source: str
    missing_policy: str = "skip"
    uses_future: bool = False
    requires: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.lookback < 0:
            raise ValueError("lookback must be non-negative")
        if self.uses_future:
            raise ValueError(
                f"feature {self.name!r} declares uses_future=True; ORION forbids this"
            )
        if not self.formula:
            raise ValueError("formula must be non-empty")
        if not self.source:
            raise ValueError("source must be non-empty")


@dataclass(frozen=True, slots=True)
class FeatureContext:
    """Inputs the feature may consume. All slices are ordered ascending by time.

    ``closes[:i+1]`` is the strict prefix up to and including bar ``i``;
    features that ever access a bar at index ``> i`` will be detected by the
    leakage tests in :mod:`orion.prediction.features.validation`.
    """

    closes: tuple[float, ...]
    highs: tuple[float, ...]
    lows: tuple[float, ...]
    opens: tuple[float, ...]
    volumes: tuple[float, ...]
    index: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("index must be non-negative")
        for label, series in (("closes", self.closes), ("highs", self.highs),
                              ("lows", self.lows), ("opens", self.opens),
                              ("volumes", self.volumes)):
            if len(series) <= self.index:
                raise ValueError(f"{label} series too short for index {self.index}")

    def prefix(self, series_name: str, length: int) -> tuple[float, ...]:
        series: tuple[float, ...] = getattr(self, series_name)
        if length < 0:
            raise ValueError("length must be non-negative")
        if length > self.index + 1:
            raise ValueError("length exceeds available history at index")
        return series[: self.index + 1][-length:]


@dataclass(frozen=True, slots=True)
class Feature:
    meta: FeatureMeta
    fn: FeatureFn

    def __call__(self, ctx: FeatureContext) -> float | None:
        return self.fn(ctx)


@dataclass(frozen=True, slots=True)
class FeatureProvider:
    name: str
    version: str
    available: bool
    detail: str

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "available": self.available,
            "detail": self.detail,
        }


def provider_status() -> Mapping[str, FeatureProvider]:
    """Return the live status of every feature backend."""
    from . import technical

    return {"technical": technical.provider()}