from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RegistryStatus(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    VALIDATING = "VALIDATING"
    APPROVED = "APPROVED"
    PRODUCTION = "PRODUCTION"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class RegistryRecord:
    name: str
    version: str
    status: RegistryStatus
    dataset: str
    metrics: dict[str, float] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    lineage: tuple[str, ...] = ()


class ImmutableRegistry:
    def __init__(self) -> None:
        self._records: list[RegistryRecord] = []

    def add(self, record: RegistryRecord) -> None:
        if any(item.name == record.name and item.version == record.version for item in self._records):
            raise ValueError("registry records are immutable and versions cannot be overwritten")
        self._records.append(record)

    def records(self, name: str | None = None) -> tuple[RegistryRecord, ...]:
        records = self._records if name is None else [item for item in self._records if item.name == name]
        return tuple(records)

    def promote(self, name: str, version: str, status: RegistryStatus) -> RegistryRecord:
        matches = [item for item in self._records if item.name == name and item.version == version]
        if not matches:
            raise KeyError(f"unknown registry record: {name}:{version}")
        current = matches[-1]
        promoted = RegistryRecord(current.name, current.version + "+" + status.value.lower(), status,
                                  current.dataset, dict(current.metrics), lineage=current.lineage + (current.version,))
        self.add(promoted)
        return promoted
