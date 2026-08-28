"""Data lineage.

Every datum that enters ORION gets a :class:`LineageRecord`. A line is
``(vendor, series_id, vendor_release_time, fetch_time, sha256)`` and
nothing else. Lineage is stored alongside the data and reported in audit
and backtest reports.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class LineageRecord:
    vendor: str
    series_id: str
    vendor_release_time: datetime
    fetch_time: datetime
    sha256: str
    n_obs: int = 0
    extra: tuple[tuple[str, str], ...] = ()

    def to_dict(self) -> dict[str, object]:
        d = asdict(self)
        d["vendor_release_time"] = self.vendor_release_time.isoformat()
        d["fetch_time"] = self.fetch_time.isoformat()
        d["extra"] = dict(self.extra)
        return d


def hash_records(records: list[dict[str, object]]) -> str:
    """Deterministic hash of a JSON-serialisable record list."""
    blob = json.dumps(records, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def now_utc() -> datetime:
    return datetime.now(timezone.utc)
