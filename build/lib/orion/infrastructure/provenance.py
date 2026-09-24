from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    artifact_id: str
    kind: str
    source: str
    content_hash: str
    metadata: dict[str, Any]
    recorded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class ProvenanceStore:
    def __init__(self) -> None:
        self._records: dict[str, ProvenanceRecord] = {}

    def record(self, artifact_id: str, kind: str, source: str, content: str, **metadata: Any) -> ProvenanceRecord:
        record = ProvenanceRecord(artifact_id, kind, source, sha256(content.encode("utf-8")).hexdigest(), metadata)
        self._records[artifact_id] = record
        return record

    def get(self, artifact_id: str) -> ProvenanceRecord | None:
        return self._records.get(artifact_id)

    def all(self) -> tuple[ProvenanceRecord, ...]:
        return tuple(self._records.values())
