"""Versioned datasets with leakage-aware splitting.

A dataset version is immutable: content hash + purge/embargo policy + split
assignment are fixed at creation. Model claims are only comparable when they
reference the identical dataset version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Sequence


@dataclass(frozen=True, slots=True)
class DatasetVersion:
    identifier: str
    content_hash: str
    rows: tuple[dict[str, Any], ...]
    feature_names: tuple[str, ...]
    created_at: datetime
    purge: int
    embargo: int

    def describe(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "content_hash": self.content_hash,
            "rows": len(self.rows),
            "features": list(self.feature_names),
            "purge": self.purge,
            "embargo": self.embargo,
        }


@dataclass(frozen=True, slots=True)
class DatasetSplit:
    train: tuple[dict[str, Any], ...]
    validation: tuple[dict[str, Any], ...]
    test: tuple[dict[str, Any], ...]
    version: DatasetVersion

    def sizes(self) -> dict[str, int]:
        return {"train": len(self.train), "validation": len(self.validation), "test": len(self.test)}


class DatasetBuilder:
    """Builds immutable dataset versions from experience rows."""

    def __init__(self, *, purge: int = 2, embargo: int = 1) -> None:
        if purge < 0 or embargo < 0:
            raise ValueError("purge and embargo must be non-negative")
        self.purge = purge
        self.embargo = embargo
        self._versions: dict[str, DatasetVersion] = {}

    def build(self, name: str, rows: Sequence[dict[str, Any]], feature_names: Sequence[str]) -> DatasetVersion:
        if not name.strip():
            raise ValueError("dataset name is required")
        if not rows:
            raise ValueError("rows must be non-empty")
        missing = [feature for feature in feature_names if any(feature not in row for row in rows)]
        if missing:
            raise ValueError(f"rows missing features: {sorted(set(missing))}")
        content_hash = sha256(repr(sorted((tuple(sorted(row.items())) for row in rows))).encode("utf-8")).hexdigest()
        identifier = f"{name}@{content_hash[:12]}"
        if identifier in self._versions:
            return self._versions[identifier]
        version = DatasetVersion(identifier, content_hash, tuple(dict(row) for row in rows),
                                 tuple(feature_names), datetime.now(timezone.utc), self.purge, self.embargo)
        self._versions[identifier] = version
        return version

    def get(self, identifier: str) -> DatasetVersion | None:
        return self._versions.get(identifier)

    def versions(self) -> tuple[DatasetVersion, ...]:
        return tuple(self._versions.values())


class SplitPolicyViolation(Exception):
    """Raised when a requested split would leak between train and test."""


def chronological_split(version: DatasetVersion, *, train_fraction: float = 0.6,
                        validation_fraction: float = 0.2) -> DatasetSplit:
    """Ordered train/validation/test split with purge + embargo gaps.

    Gaps between segments prevent information leaking across the boundary —
    the time-series analogue of shuffling, which must never be used here.
    """
    if not 0 < train_fraction < 1 or not 0 < validation_fraction < 1:
        raise ValueError("fractions must be within (0, 1)")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("train + validation must leave room for test")
    total = len(version.rows)
    train_end = int(total * train_fraction)
    validation_end = int(total * (train_fraction + validation_fraction))
    train = version.rows[: max(1, train_end - version.purge)]
    validation = version.rows[train_end + version.embargo: max(train_end + version.embargo + 1, validation_end - version.purge)]
    test = version.rows[validation_end + version.embargo:]
    if not train or not validation or not test:
        raise SplitPolicyViolation("dataset too small for the requested purge/embargo policy")
    return DatasetSplit(tuple(train), tuple(validation), tuple(test), version)


def detect_leakage(version: DatasetVersion, split: DatasetSplit) -> tuple[str, ...]:
    """Report leakage symptoms: duplicated rows across splits, overlapping keys."""
    issues: list[str] = []
    train_keys = {repr(sorted(row.items())) for row in split.train}
    validation_keys = {repr(sorted(row.items())) for row in split.validation}
    test_keys = {repr(sorted(row.items())) for row in split.test}
    if train_keys & test_keys:
        issues.append("duplicate rows in train and test")
    if train_keys & validation_keys:
        issues.append("duplicate rows in train and validation")
    if version.purge == 0:
        issues.append("no purge gap: boundary rows may leak into validation")
    return tuple(issues)
