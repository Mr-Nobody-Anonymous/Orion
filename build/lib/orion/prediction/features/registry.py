"""Lightweight in-memory feature registry."""

from __future__ import annotations

from typing import Iterable

from .base import Feature
from .technical import build_default_features


class FeatureRegistry:
    """Holds the canonical feature catalogue and lets callers look up by name."""

    def __init__(self, features: Iterable[Feature] | None = None) -> None:
        catalogue = tuple(features) if features is not None else build_default_features()
        if not catalogue:
            raise ValueError("feature registry cannot be empty")
        names = [feature.meta.name for feature in catalogue]
        if len(set(names)) != len(names):
            raise ValueError("feature names must be unique within a registry")
        self._features: dict[str, Feature] = {feature.meta.name: feature for feature in catalogue}

    def names(self) -> tuple[str, ...]:
        return tuple(self._features)

    def get(self, name: str) -> Feature:
        try:
            return self._features[name]
        except KeyError as exc:
            raise KeyError(f"unknown feature: {name}") from exc

    def all(self) -> tuple[Feature, ...]:
        return tuple(self._features.values())

    def metadatas(self) -> tuple:
        return tuple(feature.meta for feature in self._features.values())


def default_registry() -> FeatureRegistry:
    return FeatureRegistry()
