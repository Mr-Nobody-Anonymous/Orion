from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    category: str
    content: dict[str, Any]
    created_at: datetime


class MemoryStore:
    """Append-only memory contract; persistence can be replaced by a database."""

    def __init__(self) -> None:
        self._records: list[MemoryRecord] = []

    def append(self, category: str, content: dict[str, Any]) -> MemoryRecord:
        record = MemoryRecord(category, dict(content), datetime.now(timezone.utc))
        self._records.append(record)
        return record

    def find(self, category: str | None = None) -> tuple[MemoryRecord, ...]:
        if category is None:
            return tuple(self._records)
        return tuple(record for record in self._records if record.category == category)