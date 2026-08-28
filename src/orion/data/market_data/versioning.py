"""Data versioning and a small in-process local store.

A :class:`DataVersion` is a frozen record of how a snapshot was produced.
The :class:`LocalMarketDataStore` is a stdlib-only dict-backed store keyed
by ``(symbol, date)``; it is intentionally not a database.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

from .lineage import LineageRecord


@dataclass(frozen=True, slots=True)
class DataVersion:
    schema: str
    checksum: str
    created_at: datetime
    n_rows: int
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "checksum": self.checksum,
            "created_at": self.created_at.isoformat(),
            "n_rows": self.n_rows,
            "notes": list(self.notes),
        }


def make_version(
    schema: str,
    rows: list[Mapping[str, Any]],
    notes: tuple[str, ...] = (),
) -> DataVersion:
    """Create a version from a schema name and the rows that populate it."""
    payload = json.dumps([dict(r) for r in rows], sort_keys=True, default=str).encode()
    return DataVersion(
        schema=schema,
        checksum=hashlib.sha256(payload).hexdigest(),
        created_at=datetime.utcnow(),
        n_rows=len(rows),
        notes=notes,
    )


@dataclass
class LocalMarketDataStore:
    """In-process key/value store. No external dependencies.

    Keyed by ``(symbol, date)``. The store is purely a convenience for
    tests, single-process backtests, and the point-in-time harness. A
    production deployment is expected to back this with a real database.
    """

    _data: dict[tuple[str, date], dict[str, Any]] = field(default_factory=dict)
    _lineage: list[LineageRecord] = field(default_factory=list)

    def put(
        self,
        symbol: str,
        day: date,
        row: Mapping[str, Any],
        lineage: LineageRecord | None = None,
    ) -> None:
        self._data[(symbol, day)] = dict(row)
        if lineage is not None:
            self._lineage.append(lineage)

    def get(self, symbol: str, day: date) -> dict[str, Any] | None:
        return self._data.get((symbol, day))

    def history(self, symbol: str) -> list[tuple[date, dict[str, Any]]]:
        return [
            (d, dict(r))
            for (s, d), r in sorted(self._data.items(), key=lambda x: (x[0][1], x[0][0]))
            if s == symbol
        ]

    def lineage(self) -> list[LineageRecord]:
        return list(self._lineage)

    def snapshot(self, root: Path) -> Path:
        """Persist a JSON snapshot for reproducibility."""
        root.mkdir(parents=True, exist_ok=True)
        out = root / "snapshot.json"
        payload = {
            "data": [
                {"symbol": s, "date": d.isoformat(), "row": r}
                for (s, d), r in sorted(self._data.items())
            ],
            "lineage": [lr.to_dict() for lr in self._lineage],
        }
        out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return out

    @classmethod
    def from_snapshot(cls, path: Path) -> "LocalMarketDataStore":
        payload = json.loads(path.read_text(encoding="utf-8"))
        store = cls()
        for entry in payload["data"]:
            store.put(
                entry["symbol"],
                date.fromisoformat(entry["date"]),
                entry["row"],
            )
        return store
